# v0.9 Real-Training Preflight

## Decision

The frozen C1-C4 data and training code are ready for a real Qwen2.5-7B BF16 LoRA pilot. GPU
execution is temporarily blocked because all eight local A100 80GB devices are occupied by another
user's Ray/vLLM workload. The observed free memory is 12-18 GiB per device, below the 35-40 GiB
safety envelope observed for this training path. No process was interrupted and no lower-fidelity
QLoRA substitute was used.

This is an engineering pilot with `causal_status=offline_pilot_only`. The 30-task real
Host-Instrumented Round-0 gate has not run, so a future C4-C3 improvement cannot yet be attributed to
real-agent feedback refinement.

## Frozen Data

| Item | Count |
| --- | ---: |
| Source real Agent candidates | 1,799 |
| Mapped to the current task catalog | 1,799 |
| Unmapped | 0 |
| Semantic identity migrations | 450 Legal records |
| Representable real trajectories | 1,765 |
| Accepted representable trajectories | 1,101 |
| Records per C1-C4 cohort | 600 |
| Held-out evaluation records | 600 |

Every cohort contains 480 Finance, 60 Legal, and 60 Science records. The evaluation set contains 200
records per domain. Task, subject, Evidence, Evidence version, source-record, and binding overlap
between training and evaluation are all zero. C3 and C4 sample from the same 1,101-record accepted
source pool; only the allocation policy differs.

## Exact Token Audit

The audit loads the pinned local Qwen tokenizer and reuses the exact chat-template encoding,
Assistant-label mask, deterministic repetition schedule, microbatch geometry, and token-budget
checks used by training.

| Cohort | Raw input tokens | Raw supervised tokens | Scheduled records | Supervised tokens | Steps | Deviation | Longest record | Truncated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | 1,940,372 | 228,117 | 3,156 | 1,200,156 | 789 | 0.013% | 4,930 | 0 |
| C2 | 4,295,164 | 214,882 | 3,352 | 1,199,881 | 838 | 0.010% | 9,266 | 0 |
| C3 | 4,420,449 | 206,924 | 3,480 | 1,199,419 | 870 | 0.048% | 10,118 | 0 |
| C4 | 4,670,223 | 236,617 | 3,040 | 1,200,210 | 760 | 0.018% | 10,118 | 0 |

All cohorts are within the 0.5% token deviation contract and the 3,000-step safety ceiling.

## Verification

- Full repository test suite: 137 passed after the final migration and token-accounting fixes.
- Targeted training and report suite: 31 passed.
- Ruff checks pass for the changed training modules after import normalization.
- Generalization contract audit scanned 105 files with zero imports, branches, field accesses, or
  dispatches from Core into a domain implementation.
- Cross-domain Task Pattern validation passed 20/20 Legal and Science cases.
- Typed counterfactual validation passed 589/589 cases; detection was 100% and root/closure F1 was
  98.00%.
- Local Qwen2.5-7B tokenizer and model snapshot are present and revision-pinned.
- Storage has approximately 2.2 TiB available.

## Remaining Execution

1. Obtain at least one isolated A100 with 40 GiB free; four isolated devices allow C1-C4 to run in
   parallel.
2. Train C1-C4 from the same pinned model snapshot and seed.
3. Evaluate the base model and four adapters on the same 600-record held-out set.
4. Run `summarize-v09-training` to verify hashes and produce C1-C4 deltas.
5. Treat the result as pipeline evidence only until the online Round-0 gate rebuilds the refinement
   policy from real Host-Instrumented failures.
