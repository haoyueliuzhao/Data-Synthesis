# Project Full Audit, 2026-07-28

## 1. Executive decision

The repository is healthy enough for continued v0.9 development, but the current evidence supports
two different conclusions:

| Layer | Decision | Meaning |
| --- | --- | --- |
| Source, package, and architecture integrity | Passed | No missing tracked objects, package builds, and the Core/Domain boundary holds. |
| Deterministic quality framework | Passed | Tests, typing, lint, cross-domain patterns, counterfactual validation, and CCGR replay pass. |
| v0.8 artifact integrity | Passed | D1-D5 data, adapters, predictions, and stored schemas can be reloaded and reconciled. |
| v0.9 offline algorithm MVP | Passed with limitations | CCGR is deterministic and auditable, but Round 0 uses typed counterfactuals rather than real model failures. |
| v0.9 training-utility claim | Not established | C1-C4, multi-seed training, the online gate, and an external benchmark have not been executed. |

Overall status: `engineering_pass_experimental_conditional`.

## 2. Audit scope and baseline

- Git branch: `main`
- Baseline commit: `5fccfa35c2962e41a2fa8b25c507e4c853696d82`
- Worktree: dirty before this audit; existing v0.8.1 and v0.9 work was preserved.
- Python source files: 171
- Test files: 22
- Python lines across `src/` and `tests/`: 38,766
- Project footprint: 15 GiB, including a 7.2 GiB virtual environment and 7.2 GiB artifacts.
- Archived financial lake: 45 GiB.
- `/data1` free capacity: 2.2 TiB.

The audit covered Git integrity, architecture boundaries, package metadata, dependency security,
tests and coverage, artifact schemas and hashes, training outputs, GPU execution, and experimental
validity.

## 3. Defects fixed during the audit

### 3.1 CCGR exposure denominator and stale cell identity

`aggregate_cell_feedback()` counted every task in `task_cells` as an observed exposure even when no
`FeedbackExposure` existed. Partial or failed online runs could therefore hide coverage gaps and
dilute per-cell defect and capability rates.

The implementation now:

- counts only explicitly exposed task IDs;
- rejects feedback without an exposure;
- rejects `ClauseFeedback.cell_id` values that disagree with the task's pinned synthesis cell;
- keeps unobserved cells at zero exposure so their target coverage gap remains visible.

Two regression tests cover the missing-exposure and stale-cell cases.

### 3.2 Vulnerable training dependency and unsafe model-loading surface

The migrated environment contained `transformers 4.52.4`. `pip-audit` initially reported 16 known
vulnerabilities, including unsafe untrusted model or checkpoint paths. The project also allowed all
`transformers>=4.52,<5` versions.

The training contract now requires:

- `transformers>=5.14.1,<6`;
- `safetensors>=0.8,<1`;
- immutable 40-64 hexadecimal revisions for remote models;
- `trust_remote_code=False` for tokenizer and model loading;
- `use_safetensors=True` for model loading;
- a local `adapter_model.safetensors` before adapter evaluation.

The active environment was upgraded to `transformers 5.14.1`; the final dependency audit reports no
known vulnerabilities. The local CUDA build of Torch and the two editable local packages are not
resolvable through PyPI and remain explicitly listed as unaudited by `pip-audit`.

### 3.3 Public graph API export corruption

`core.graph.__init__` assigned `__all__` twice. The second assignment silently removed the graph
schema, builder, and extractor from the declared public API. It now has one complete export list and
a regression test verifies every exported symbol.

### 3.4 Declared Python 3.10 support

`core.release.validation` imported `datetime.UTC`, which requires Python 3.11 despite
`requires-python >=3.10`. It now uses `timezone.utc`.

### 3.5 Environment and generated-output hygiene

- Editable package metadata was stale at `0.8.0`; it was rebuilt and now agrees with code at `0.9.0`.
- MyPy now checks all project source while skipping third-party stub traversal, avoiding NumPy 2.5
  syntax leaking into the Python 3.10 target check.
- `build/` and `.coverage` are now ignored so package and coverage commands do not pollute Git status.
- Ruff excludes generated `build/` output.

## 4. Verification results

### 4.1 Code and package gates

| Check | Result |
| --- | --- |
| `pytest -q` | 131 passed in 86.03 seconds |
| Coverage | 81% overall, 12,827 statements |
| `ruff check .` | Passed |
| `mypy src/trusted_synthesis` | Passed, 171 source files |
| `git diff --check` | Passed |
| Wheel build | Passed, `trusted_data_synthesis-0.9.0-py3-none-any.whl` |
| `pip check` | No broken requirements |
| `pip-audit` | No known vulnerabilities among resolvable packages |
| Git object integrity | Passed; only unreachable dangling objects were reported |
| Secret scan | No checked-in `sk-...` credential; configs use environment variable names only |

Repository-wide Ruff formatting is not yet a hard gate: 19 existing files would be reformatted. This
is maintenance debt, not a behavioral failure, and was not converted into broad unrelated churn.

### 4.2 Generalization and cross-domain gates

The `generalization_contract.v1.2` audit scanned 105 Core, Runtime, and Architecture files:

- discovered domains: finance, legal, science;
- Core domain imports: 0;
- Core domain branches: 0;
- Core domain-field interpretation: 0;
- dynamic domain imports: 0;
- domain dispatch in Core: 0.

The non-financial task-pattern suite compiled 20 legal and science tasks. Reference pass rate, clean
candidate pass rate, contract-decision parity, binding-clause coverage, and difficulty-clause
coverage were all 100%.

### 4.3 Counterfactual quality calibration

The 30-task finance/legal/science suite generated 589 typed counterfactuals:

- mutation validity: 100%;
- detection F1: 1.0;
- root-cause F1: 0.9800469;
- failure-closure F1: 0.9800469;
- minimality pass rate: 100%;
- mean minimality score: 0.9911177.

The residual error is over-localization in a few trajectory mutations, especially `replace_tool` and
some failed-step cases. Detection is reliable, but root localization should not be described as
perfect.

## 5. Data and experiment artifact audit

### 5.1 v0.8 D1-D5 data

The Qwen2.5-7B materialization contains five 600-record training cohorts plus 600 evaluation records,
for 3,600 parsed records. Every cohort contains 200 finance, 200 legal, and 200 science records.

The stored integrity audit confirms:

- all dataset hashes match the manifest;
- duplicate record IDs: 0;
- private-field leaks: 0;
- exact train/evaluation prompt overlap: 0;
- train/evaluation task overlap: 0;
- accepted real-agent candidates: 1,101;
- critic-reviewed accepted candidates: 765.

Important interpretation: `real_agent` describes real DeepSeek trajectories, but the underlying
finance, legal, and science tasks are still generated from parameterized contract fixtures. This is
stronger than a scripted trajectory and weaker than native-domain production evidence.

### 5.2 Cohort contrast limitation

Training/evaluation leakage is absent, but training cohorts intentionally reuse many task identities.
The strongest contrast concern is D3 versus D5:

- shared task IDs: 384 of 600 per cohort;
- shared prompts: 384;
- shared assistant targets: 384;
- task-set Jaccard similarity: 0.470588.

D3 and D4 share 321 task IDs; D4 and D5 share 303. This does not invalidate the models, but it limits
the strength of causal claims that D5's gain comes solely from Quality Critic selection. Future v0.9
cohorts need an explicit matched-overlap contract and a reported changed-cell budget.

### 5.3 v0.8 training and evaluation

All five LoRA cohorts completed 600 steps. Each final adapter:

- is a readable Safetensors file;
- contains 392 tensors and 20,185,088 trainable parameters;
- occupies 80,792,096 bytes;
- has a distinct SHA-256 digest.

All six prediction artifacts contain exactly 600 rows and reload under the current schema.

| Model | End-to-end rate |
| --- | ---: |
| Base | 0.0000 |
| D1 Random Synthetic | 0.5250 |
| D2 Reference Workflow | 0.9167 |
| D3 Contract Filtered | 0.5400 |
| D4 Contract + Counterfactual Calibration | 0.5267 |
| D5 Quality Critic Selection | 0.5667 |

D2 is the current best cohort. These results establish that the training/evaluation machinery ran;
they do not establish the proposed v0.9 CCGR training utility.

### 5.4 v0.9 offline CCGR MVP

Rebuilding the 9-task v0.9 pilot produced byte-identical report and manifest hashes:

- source tasks: 9;
- synthesis cells: 9;
- valid and detected counterfactual cases: 169;
- calibrated clause kinds: 9;
- calibration coverage: 75%;
- feedback routes: 95 capability-gap signals;
- Full CCGR total variation distance: 0.42177565;
- Full CCGR KL divergence: 0.50769855;
- status: passed.

This slice has no synthesis-defect root, so the `beta=0` ablation is not identifiable here. It also
sets `round0_real_agent_feedback=false`; it validates algorithm mechanics, not the full causal loop.

## 6. Hardware and runtime validation

- CPU: 2 x Intel Xeon Platinum 8368, 76 physical cores, 152 threads.
- RAM: 1.0 TiB total, about 983 GiB available during final audit.
- GPU: 8 x NVIDIA A100-SXM4-80GB.
- Torch: `2.7.1+cu128`, CUDA visible on all eight devices.

All eight GPUs completed the same CUDA matrix operation with identical checksums. A real one-step
Qwen2.5-7B LoRA training smoke test then completed on one A100 using the secure dependency stack:

- Transformers 5.14.1;
- PEFT 0.15.2;
- completed steps: 1;
- final loss: 0.416576;
- peak allocated GPU memory: 26,294,238,720 bytes;
- adapter saved successfully.

A three-record adapter evaluation also completed and generated parseable JSON. Its end-to-end score
was zero, as expected for a one-step smoke adapter; that run proves runtime compatibility only.

## 7. Remaining findings

### P1: required before a v0.9 training-utility claim

1. Run the 30-task online Host-Instrumented gate using securely injected credentials. No LLM API key
   was present during this audit, so no live provider call was made.
2. Materialize and train the actual v0.9 comparison cohorts C1-C4 at equal supervised-token budgets.
3. Execute at least three seeds and report confidence intervals, target-root reduction, non-target
   retention, coverage, and allocation stability.
4. Add a native external benchmark. The current manifest explicitly says `not_executed`.
5. Include real synthesis-defect failures so the defect-suppression term and binding tightening are
   empirically identifiable.
6. Move beyond parameterized fixtures for at least one native finance, legal, and science slice.

### P2: engineering debt

1. Add a reproducible dependency lock or container digest. Historical result files record package
   versions, but installation is still governed by dependency ranges.
2. Raise integration coverage for CLI (0%), finance pilot runner (17%), sampler (33%), training
   orchestration (34%), and evaluation orchestration (45%). GPU smoke tests currently run outside
   the unit coverage process.
3. Either integrate or remove the unused `ReasoningPath` model; the active architecture uses proof
   subgraphs rather than this unreferenced path object.
4. Apply Ruff formatting in a dedicated mechanical change and make format checking a CI gate.

## 8. Release recommendation

Proceed with v0.9 online validation and cohort materialization. Do not yet describe CCGR as improving
training utility, and do not compare D3/D5 as a clean causal ablation without disclosing their 64%
per-cohort task overlap. The implementation is now fit to run the experiment; the experiment itself
is not yet complete.

Machine-readable supporting results are under
`artifacts/audit/project_full_audit_20260728/`.
