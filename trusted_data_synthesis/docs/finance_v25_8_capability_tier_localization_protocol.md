# Finance v25.8 Capability Tier Localization Protocol

## Purpose

v25.8 repairs the invalid Direct arm observed in v25.7 and inserts an
empirical tier-localization stage before another full Pro/Flash calibration.
It does not alter the frozen v25 capability-sensitive task population or
reinterpret the immutable v25.7 result.

The experiment distinguishes three claims that must not be conflated:

1. the v25 task population is structurally capability-identifiable;
2. the API runtime can execute those tasks under a bounded public contract;
3. a task tier lies near the empirical boundary of a particular model and
   runtime.

Only the first claim was established by v25. The second is requalified after
the Direct repair, and the third is the target of this protocol.

## v25.7 Diagnosis

The v25.7 artifact remains frozen. Its Direct trajectories frequently reached
the correct answer and completed their operation and verification steps, but
were rejected by `allowed_tool_compliance`: the task exposed archive tools
while the Direct compiler emitted `evidence.search` and registered operation
tools. The resulting Direct zero-valid rate is therefore not a model response
measurement.

The Scripted and Autonomous Frontier cells exposed a different problem. Their
responses were commonly at the floor, so an all-Frontier design could not
determine whether Easy, Frontier, or Hard was the informative tier. Repeating
1,680 Frontier rollouts would spend API budget without resolving that
identification problem.

## Contract Revisions

### Runtime-visible tools

The runtime binding now freezes `public_allowed_tools` per task and runtime.
For Direct Fixed Retrieval, these tools are compiled from the task program via
the operation registry and include `evidence.search`. Scripted and Autonomous
runtimes continue to use the frozen archive tool manifest. The verifier checks
the same binding field, so compiler and verifier share one immutable public
tool identity.

### Call budget

The task structure distinguishes tool actions from a model-level stop
decision. A Hard Scripted task may contain 19 explicit tool calls while its
structural minimum is 20 because the final stopping decision is not a tool.
v25.8 therefore freezes:

- maximum required tool calls: 20;
- maximum failed recovery calls: 3;
- maximum total calls: 23.

The runtime does not fabricate an extra tool call to satisfy the structural
counter.

### Immutable stage identities

Schema and artifact versions are advanced for the runtime binding, boundary
contract, rollout record, analysis report, and Beneficiary gate. A v25.7
artifact cannot authorize a v25.8 stage.

## Stage 1: Runtime Qualification

Qualification uses seven Frontier anchor tasks, two models, three runtimes,
and three replicas:

```text
7 families x 2 models x 3 runtimes x 3 replicas = 126 rollouts
```

It evaluates protocol execution only:

- API and bounded JSON resolution;
- bounded tool execution and terminal emission;
- observation replay;
- public authority and tool compliance;
- identity and budget integrity.

Semantic answer quality is reported but is not a Runtime hard gate. A capable
runtime must be allowed to expose model failure.

## Stage 2: Tier Localization

The localization partition contains one pre-registered task per capability
family and tier. The Frontier task is the Qualification anchor; Easy and Hard
are separate tasks. Qualification and localization therefore share only their
declared Frontier anchors, while the later calibration set remains disjoint.

```text
7 families x 3 tiers x 2 models x 3 runtimes x 5 replicas = 630 rollouts
```

For each Model x Runtime x Family x Tier cell, the report records:

- technical resolution rate;
- semantic answer accuracy;
- valid-success probability;
- Wilson 95% interval;
- empirical Bernoulli information, `p * (1 - p)`.

For each Runtime x Family, a common tier is selected for Pro and Flash only
when both model cells satisfy the runtime technical threshold and at least one
model has valid-success probability in the pre-registered interval [0.10,
0.90]. The eligible tier maximizing mean Bernoulli information is selected;
ties resolve deterministically as Frontier, Easy, then Hard.

The report also checks Easy >= Frontier >= Hard response monotonicity. A task
family can be structurally monotone yet empirically non-monotone; the latter is
reported rather than hidden by aggregate accuracy.

## Authorization Rules

The stage decision is fail-closed:

- no technically usable boundary tier: `task_or_runtime_redesign_only`;
- an informative tier exists but is not Frontier for every runtime/family:
  `calibration_contract_refreeze_required`;
- all 21 Runtime x Family cells select Frontier:
  `paired_capability_calibration`.

The second outcome is not a failure. It means the model-visible calibration
population must be re-frozen around empirically selected tiers before running
the 1,680-rollout paired experiment.

Regardless of localization outcome, this stage forbids:

- Beneficiary Frontier Screening;
- Exact Target measurement;
- GP-C evaluation;
- Authorization Objective access;
- VTDO distribution updates.

Those stages require a separately frozen, passing calibration artifact and the
subsequent empirical capability-information audit.

## Interpretation Boundary

Tier localization estimates response boundary, not Contribution. It cannot
show that Flash is a better Explorer, that the seven capability axes are fully
identified in model responses, or that any trajectory state exceeds the
minimum practical Contribution effect. It only determines whether the next
paired calibration has an observable response regime under each runtime.

