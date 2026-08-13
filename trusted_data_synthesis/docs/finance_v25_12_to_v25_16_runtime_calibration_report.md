# Finance v25.12-v25.16 Runtime Calibration Report

> Historical protocol note (2026-08-13): this document records the original v25.12-v25.16
> decision and its then-frozen 95% mixed Technical gate. Runtime Resolution v2 does not reinterpret
> those immutable results; it replaces the gate for new experiments by separating measurement
> integrity from model correctness. See
> `docs/finance_v25_17_v25_18_runtime_resolution_and_information_report.md`.

## Decision

The Flash-first experiment remains fail-closed. DeepSeek V4 Flash is the only model called in
v25.12-v25.16. Pro is retained only as a future sparse anchor and received zero calls because the
Flash technical gate never passed. Information Matrix evaluation, model ranking, Beneficiary
screening, Exact Target, GP-C, and production Contribution all remain forbidden.

v25.16 is the strongest result so far. Its valid-success rate is 70.24%, semantic-answer accuracy
is 77.38%, and repeated-failed-call rate is 7.14%. The last value is lower than the frozen v25.12
source rate of 13.33%. The preregistered technical threshold is nevertheless 95%; v25.16 reaches
only 77.38%, so the next permitted stage remains `runtime_contract_repair_only`.

## Frozen denominator

Each calibration release uses the same deterministic development slice:

- 7 capability families;
- Easy, Frontier, and Hard workflow tiers;
- Scripted Tool and Autonomous Agent runtimes;
- 21 tasks, 42 bindings, and 2 replicas per binding;
- 84 complete Flash rollouts per release;
- the same source population, selection salt, tool environment, and model family;
- no Pro calls and no downstream objective access.

This is a protocol calibration set. It is not an authorizing capability result and is not used to
estimate model ranking or Contribution.

## Runtime repair sequence

| Release | Main intervention | Technical | Valid | Semantic | Repeated failure | Budget | API calls | Tokens | Cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v25.13 | bounded retry and answer constraints | 86.90% | 33.33% | 33.33% | 13.10% | 100.00% | 786 | 3,754,718 | 0.332303 |
| v25.14 | Program-compiled DAG and exact terminal decimals | 40.48% | 34.52% | 38.10% | 51.19% | 98.81% | 709 | 3,588,052 | 0.385625 |
| v25.15 | separate retrieval scheduling from calculation progress | 63.10% | 61.90% | 63.10% | 16.67% | 91.67% | 955 | 5,301,538 | 0.541992 |
| v25.16 | exact Evidence-role resolution, operand order, and terminal operation binding | 77.38% | 70.24% | 77.38% | 7.14% | 91.67% | 914 | 5,648,651 | 0.613044 |

The four calibration runs used 3,364 Flash API calls, 18,292,959 model tokens, and an estimated
USD 1.872963. The prior v25.12 full-support run used 5,842 calls, 24,884,118 tokens, and USD
2.224521. Costs are provider-telemetry estimates, not an extrapolation from rollout count.

## What changed

### Program is the single arithmetic authority

The public operation contract is compiled from the frozen Oracle `TaskProgram`. It no longer uses
a second family-specific formula implementation. Every immutable calibration contract validates
the canonical hash of the public contract against a fresh compilation from the unchanged Oracle
Program.

The contract freezes:

- ordered operator nodes and exact parameters;
- Evidence and prior-operation input roles;
- selectors for prior operation outputs;
- output node and answer schema;
- signed arithmetic and no-rounding policy;
- Solver, prompt, runtime, toolset, operation-contract, and repair-policy versions.

### Operation calls are fail-closed

The Host now reconstructs Program progress from successful public observations. A calculator call
is accepted only when it matches the next Program node, including operator, parameters, operand
identity, operand order, and exact prior `operation_ref`. Missing selected Evidence yields a typed
prerequisite rejection. A semantically wrong but syntactically valid operation yields an exact
argument-patch rejection.

The final answer must copy the exact terminal calculator output without numeric coercion or
rounding. It is bound to the terminal Program operation, not merely the last calculator call.

### Recovery is explicit

Identical failed calls are never executed twice. Typed selector failures expose a public argument
patch. Operation failures distinguish between:

- `argument_patch_required`; and
- `prerequisite_action_required`.

Mutation tests cover unchanged retries, invented operation references, wrong operand order,
missing Evidence selection, early final answers, and approximate numeric copies.

## v25.14 negative result and correction

v25.14 exposed a Host-level scheduling contradiction. A Scripted runtime could freeze the next
tool as `query_structured_fact` while the newly visible Operation Progress demanded `calculator`.
Flash then placed calculator arguments in the forced query tool. Fail-closed validation correctly
rejected the call, but the reported repeated-failure rate measured the induced conflict rather
than a useful recovery behavior.

v25.15 limited Operation Progress to actual calculation steps in Scripted mode. This raised valid
success from 34.52% to 61.90% and reduced repeated failures from 51.19% to 16.67%.

## v25.16 result

Before execution, all 63 Program input variables were checked against their frozen public corpora:
63 resolved uniquely, none were missing, and none were ambiguous. All 84 requested rollouts were
recorded. Bounded JSON, Observation replay, authority integrity, and infrastructure success were
100%.

The 19 non-completed trajectories separate into:

- 7 model-token-budget failures;
- 6 stop-rejection-budget failures;
- 6 identical-failed-action blocks.

These are runtime-calibration failures. They are not evidence that the capability distribution is
informative, and they do not authorize Pro anchors or downstream contribution experiments.

## Question generation boundary

The financial task questions and instructions in these releases are generated deterministically
from Task Pattern and TaskProgram contracts. DeepSeek is not used to polish, paraphrase, or
anti-normalize the questions. API calls generate Agent decisions and tool trajectories only.

This separation is deliberate: adding LLM question rewriting inside this capability experiment
would confound task semantics, runtime repair, and Explorer behavior. A future language-diversity
release may use a separate rewrite stage only if it preserves a frozen semantic contract and
passes an independent round-trip parser and verifier.

## Next permitted work

Do not run the Information Matrix or Pro anchor yet. The next development release should target
only the 19 residual failure shapes and then use a fresh held-out calibration slice. In particular:

1. hide the full Operation DAG from non-calculator Scripted steps so normalization cannot be
   preempted by a later arithmetic action;
2. provide a bounded Host summary of selected Evidence and operation references to reduce repeated
   prompt tokens without increasing the 120,000-token budget;
3. allow a typed corrective tool action after a rejected final answer when the Program remains
   incomplete;
4. report terminal failure causes separately from blocked unsafe attempts;
5. require at least 95% technical pass, improved semantic direction, and lower repeated-failure
   rate on a fresh slice before any full Flash information confirmation.

Until those gates pass, the scientific status is:

```text
Flash runtime semantics: materially improved but not authorized
Pro sparse anchor: retained, not called
Information Matrix: not evaluated
Model ranking: not authorized
Beneficiary / Exact Target / GP-C: not evaluated
Production Contribution: 0
```
