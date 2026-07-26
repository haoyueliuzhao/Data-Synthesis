# Finance Synthesis Pilot

## Purpose

This pilot validates the finance path before extending the framework to legal or
scientific reasoning:

    Pinned finance KG
    -> Finance Evidence IR
    -> stratified task bindings
    -> gold bundle + distractor corpus
    -> Proof Graph and Task Program
    -> Reference and public-only Candidate
    -> controlled mutations
    -> independent quality evaluation
    -> accepted-only release

Passing deterministic Reference workflows alone is not considered sufficient.
The pilot must also accept clean public-only Candidates, reject corrupted
Candidates without receiving mutation labels, localize their failed hard gates,
and reproduce all stable IDs in a second full run.

## Frozen Configuration

The checked-in profile is config/finance_pilot_small.json:

| Item | Value |
| --- | ---: |
| Evidence scanned | 20,000 |
| Gold tasks | 24 |
| Task families | 4 |
| Distractors per task | 6 |
| Mutated Candidates | 275 |

The task mix is evenly split across fact retrieval, comparison, temporal growth,
and temporal average. Temporal average uses an explicit three-lookup plus
aggregate DAG, giving the pilot program depths of 1, 3, and 4.

## Actual Result

The run against KG build kg_20260711_062123_bc4b4394 produced:

| Metric | Result |
| --- | ---: |
| Evidence domain-valid rate | 100% |
| Task compilation | 24 / 24 |
| Reference accepted | 24 / 24 |
| Clean Candidate accepted | 24 / 24 |
| Mutated Candidate rejected | 275 / 275 |
| Critical false acceptance rate | 0% |
| Clean false rejection rate | 0% |
| Failure localization | 100% |
| Semantic split leakage | 0 |
| Independent full-run artifact differences | 0 |

Every configured gate passed, so the architecture is feasible for the observed
global financial numeric resolved track.

## Defect Found By The Pilot

The first run accepted only 20 of 24 growth tasks. Executor and independent
Verifier used algebraically equivalent growth formulas with different Decimal
operation order. Non-terminating values such as 1.13 to 1.62 therefore differed
in their final decimal place under an exact-output contract.

The Verifier now follows the frozen formula:

    (later - earlier) / abs(earlier) * 100

The growth verifier and semantic versions were raised to 1.0.1, its formula ID
is explicit, and a non-terminating Decimal regression test protects the contract.
The second Pilot run then passed all 24 clean workflows.

## Mutation Coverage

The evaluator rejected and localized missing evidence, wrong entity, time shift,
predicate mismatch, arithmetic error, wrong final answer, citation mismatch,
unsupported investment claims, Oracle leakage, disallowed tools, failed steps,
and multi-error combinations.

The theoretical matrix contains 288 task/mutation combinations. The runner
materialized 275: arithmetic mutation does not apply to six lookup-only tasks,
and seven tasks lacked a suitable predicate distractor in their six-item corpus.
This shortfall is reported rather than silently counted as a passing test.

## Coverage Boundary

This is not yet a production finance release. The pinned KG's eligible historical
facts are sourced from SEC Company Facts, FRED, and World Bank. No
mainland/Hong Kong/Macau graph-ready fact was available to this adapter, so all
24 tasks are Global. The Pilot also excludes:

- live LLM or Agent Candidates;
- human/evaluator agreement;
- open retrieval and entity disambiguation;
- ratio-after-comparison and multi-company growth DAGs;
- legal and science non-lookup reasoning.

Accordingly the result is recorded as:

    architecture_feasible = true
    production_ready = false

## Reproduction

Run from /workspace/Data Synthesis/trusted_data_synthesis:

    PYTHONPATH=src python -m trusted_synthesis.cli finance-pilot \
      --config config/finance_archive.json \
      --pilot-config config/finance_pilot_small.json \
      --output-dir artifacts/finance_pilot/small_v1

The output directory contains Task Packages, task contexts, Reference workflows,
clean and mutated Candidates, all assessments, a Release Manifest, and JSON/Markdown
reports. artifacts/ is ignored by Git and the archive remains read-only.
