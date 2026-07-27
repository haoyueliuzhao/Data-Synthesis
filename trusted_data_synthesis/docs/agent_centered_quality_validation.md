# v0.8 Agent-Centered Quality Validation

## Purpose

v0.8 moves the framework from validating synthetic correctness to measuring real agent
behavior. It does not replace the v0.7 Quality Contract or Typed Counterfactual Engine.
It adds real model trajectories, a stable Quality Vector, advisory critic labels,
quality-aware selection, and a frozen training-utility experiment protocol.

```text
Task Release
  -> Candidate Agent Pool
  -> Model-controlled retrieval where applicable
  -> Real Candidate Trajectory
  -> Quality Contract Runtime
  -> Quality Vector + Root Failure Analysis
  -> Contract-authoritative Quality Selection
  -> D1-D5 Training Utility Protocol
```

## Candidate Agent Contract

`AgentSolver` receives only `TaskPublicSpec` and an `EvidenceToolRuntime`. The model never
receives the Oracle Contract, gold Evidence IDs, reference answer, Contract decision, or
Quality Vector. The normalized trajectory preserves model-selected Evidence, reported
operation outputs, final answer, and citations. Normalization adds stable workflow fields;
it does not replace a wrong answer with the oracle answer.

The response contract rejects unknown operators, non-retrieved Evidence IDs, invalid
operation output shapes, non-topological references, and PLAN_GIVEN parameter drift.
Financial or domain-semantic mistakes remain visible and are judged by independent replay.

## Retrieval And Planning Tracks

| Track | Public information | Model behavior |
| --- | --- | --- |
| Resolved | normalized entity, predicate, time, bounded corpus | host executes the frozen public query |
| Semi-open | aliases, partial constraints, bounded corpus | model emits a typed search query, then answers |
| Open | natural-language task and bounded corpus | model formulates a typed query, selects Evidence, then answers |
| PLAN_GIVEN | public operation skeleton | model preserves nodes, operators, parameters, and dependencies |
| PLAN_HIDDEN | public operation catalog only | model proposes a topological operation DAG |

Search and answer are separate contracts for Semi-open and Open. The host always restores
the immutable corpus boundary. Search responses cannot represent Evidence IDs or oracle
fields. Broad retrieval is allowed so hard in-scope distractors remain observable; semantic
selection is evaluated separately.

## DeepSeek V4 Pro Routing

The reference smoke profile is `config/deepseek_v4_pro_agent_smoke.json`.

* requested model: `deepseek-v4-pro`;
* provider model discovery: enabled and cached per client;
* silent fallback: disabled;
* response mode: strict JSON object;
* Agent and Critic contract repair: at most one follow-up request;
* credential source: `DEEPSEEK_API_KEY` environment variable only;
* cost estimate: intentionally unset until an audited provider tariff is frozen.

The client records model requested/selected/returned, token usage, latency, response hashes,
contract status, and fallback status. It never records the credential or an Authorization
header. Inline credential headers are rejected by configuration validation.

## Quality Vector

Every fully evaluated candidate is projected from authoritative clause results onto:

```text
evidence
program
trajectory
citation
claim
```

Fatal, quarantine, and diagnostic clauses receive distinct weights. A non-applicable
dimension remains `null`; it is not reported as a perfect score. Unmapped diagnostic
dimensions fail closed so a new domain clause cannot silently disappear from the vector.

## Quality Critic

The critic receives the public task, Evidence corpus, candidate trajectory, and a structural
Contract summary. It does not receive the Contract assessment or label. Samples are selected
by domain, candidate source, and Contract decision so both real trajectories and typed
counterfactual negatives are reviewed.

Critic output is always `model_advisory`. It cannot:

* masquerade as a human annotation;
* turn a Contract rejection into an accepted sample;
* establish human alignment targets;
* replace deterministic replay or root-cause localization.

Human and model agreement statistics are stored separately. With no human annotations,
human agreement remains `null`.

## Quality-Aware Selection

Selection first applies hard Contract decisions, then minimum Quality Vector thresholds,
then an optional critic probability threshold. Ranking combines overall vector quality,
the minimum applicable dimension, and advisory critic confidence. Deterministic strata can
cap concentration by domain, retrieval track, planning track, and candidate source.
An accepted sample outside the critic review budget receives a neutral `0.5` advisory prior,
not a perfect score, so review coverage cannot silently bias selection.

## Training Utility Protocol

v0.8 freezes five comparable cohorts:

| Cohort | Data source |
| --- | --- |
| D1 | random synthetic candidates |
| D2 | deterministic reference workflows |
| D3 | Contract-filtered real candidates |
| D4 | Contract-filtered candidates plus typed counterfactuals |
| D5 | Quality-Critic-ranked candidates that already passed Contract gates |

The protocol fixes model, seed, training method, optimizer policy, steps, metrics, and
held-out domains. Its status is `planned`. A completed utility result is schema-valid only
when all D1-D5 run IDs and metric sets are present.

The smoke runner does not currently materialize an independent random synthetic pool.
Consequently D1 is explicitly recorded as `planned` with no sample IDs; real Agent
candidates are never relabeled as random synthetic data. Cohorts with frozen IDs are marked
`prepared`, which prevents protocol identity from overstating experimental completion.

## Artifacts

`validate-agents` writes:

```text
agent_validation_report.json
agent_validation_samples.jsonl
quality_critic_dataset.jsonl
training_utility_protocol.json
manifest.json
```

The manifest freezes model configuration, agent and critic Prompt manifests, Quality Vector
policy, selection policy, critic dataset, and training protocol hashes. The report separates
API success, normalized trajectories, Contract decisions, critic attempts, critic failures,
token usage, retrieval/planning slices, domains, failure families, and root locations.

## Commands

```bash
export DEEPSEEK_API_KEY="<provided outside the repository>"

trusted-synthesis validate-agents \
  --agent-config config/deepseek_v4_pro_agent_smoke.json \
  --output-dir artifacts/agent_validation/v08_deepseek_smoke \
  --output artifacts/agent_validation/v08_deepseek_smoke_report.json
```

## Claims And Non-Claims

Offline Contract tests establish API stability, three-domain normalization, search isolation,
PLAN_GIVEN/PLAN_HIDDEN replay, counterfactual rejection, and critic-label separation. A small
online smoke establishes provider and prompt compatibility only. It does not establish the
human-alignment targets or downstream training gains proposed by the v0.8 methodology.
