# Finance v26 Bridge And State-support Revision Report

Date: 2026-08-17

## Scope

This revision implements the audit requirement to separate capability-boundary measurement from
state-support discovery. It intentionally breaks the earlier Bridge artifact identities instead
of preserving a scientifically ambiguous contract.

## Implemented Changes

1. Core now freezes one scaffold-invariant state mapping contract for all ladder levels and stores
   scaffold trace outside quotient-state identity.
2. Static ladder gates are now seven explicit checks, including incremental necessity,
   withdrawal readiness, and state-mapping invariance.
3. Finance Bridge uses five mechanism-specific Estimands rather than one generic fidelity score.
4. The 576 Development rollouts no longer require three-state occupancy; state count is diagnostic.
5. The minimum passing level is selected once per mechanism. Higher levels are diagnostic.
6. Fresh Confirmation uses a separate static authorization for 24 new tasks and can authorize only
   state-support discovery.
7. State-support discovery has its own 18-rollout task contract, Wilson lower bounds, conditioned
   acceptance estimates, and immutable per-state materialization budgets.
8. Withdrawal readiness remains a static gate; Withdrawal Transfer is a post-training Estimand.
9. Compiler Bridge and fixed-scaffold VTDO comparisons are represented as separate causal
   experiments.

## Fail-closed Cases

Tests now reject missing mechanism Estimands, incomplete rollout accounting, per-task scaffold
selection, cross-level state-mapping drift, reused compiled task conditions, fresh-task reuse,
missing confirmation static admission, fewer than three accepted states, zero conditioned
acceptance, quota transfer, and task-condition mutation.

## Execution Boundary

This is a protocol and implementation revision. It does not consume external model tokens and it
does not launch a GPU job. A new immutable preflight must pass before any fresh Finance task is sent
to an external model.

The resulting v26.3 preflight passed all 23 checks. The complete repository validation passed Ruff,
Mypy over 335 source files, and 796 Pytest tests. The preflight recorded zero Flash calls, zero Pro
calls, and zero GPU jobs, and authorizes only `v26_1_joint_compilation_admission`.
