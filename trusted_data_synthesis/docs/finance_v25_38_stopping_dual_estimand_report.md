# Finance v25.38 Stopping Dual-Estimand Development

## Decision

- Runtime measurement ready: `true`
- All Shapes admitted on `Y_stop`: `false`
- Dual-estimand policy frozen: `false`
- Next stage: `stopping_shape_redesign_only`

## Estimand Separation

| Response | Purpose | Rate | May rescue another response? |
| --- | --- | ---: | --- |
| `stopping_behavior_success` | capability / Shape information | 0.8568 | no |
| `full_valid_trajectory_success` | valid training support | 0.5521 | no |
| `answer_semantic_success` | diagnostic only | 0.5729 | no |
| `terminalization_success` | diagnostic only | 0.5729 | no |

## Shape Results

| Shape | Role | Y_stop | Y_valid | Y_sem | I_stop | I_valid | Boundary | Nonzero | Effective | Max share | LCB | Train-valid | Admit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `authority_coverage_gap` | `boundary_candidate` | 0.6719 | 0.4688 | 0.4844 | 1.2656 | 1.5625 | 7 | 7 | 6.195 | 0.198 | 0.562500 | 30/64 | yes |
| `contextual_resolution_choice` | `boundary_candidate` | 0.5000 | 0.3125 | 0.3281 | 1.2188 | 1.4062 | 7 | 7 | 6.298 | 0.192 | 0.515625 | 20/64 | no |
| `partial_required_evidence` | `boundary_candidate` | 0.9688 | 0.5625 | 0.5781 | 0.2188 | 1.4375 | 2 | 2 | 2.000 | 0.500 | 0.000000 | 36/64 | no |
| `single_dimension_conflict` | `boundary_candidate` | 1.0000 | 0.5625 | 0.6406 | 0.0000 | 1.7500 | 0 | 0 | 0.000 | 0.000 | 0.000000 | 36/64 | no |
| `verified_extra_call_cost` | `runtime_control` | 1.0000 | 0.7500 | 0.7500 | 0.0000 | 0.7812 | 0 | 0 | 0.000 | 0.000 | 0.000000 | 48/64 | yes |
| `verified_extra_call_error_risk` | `runtime_control` | 1.0000 | 0.6562 | 0.6562 | 0.0000 | 1.2500 | 0 | 0 | 0.000 | 0.000 | 0.000000 | 42/64 | yes |

## Support Layers

- Mechanism-observable Shapes: `3/6`
- Valid training trajectories: `212/384`
- Valid training support ready: `true`
- Contribution-authorized support: `false`
- Cross-estimand rescue: `false`

## Accounting

- Rollouts: `384/384`
- API calls: `4288`
- Model tokens: `22968208`
- Configured cost estimate: `$2.200525`
- Pro calls: `0`
- Beneficiary / Exact Target / GP-C / Contribution: `not evaluated`

## Failures

- `shape:contextual_resolution_choice:between_task_heterogeneity`
- `shape:partial_required_evidence:maximum_single_task_information_share`
- `shape:partial_required_evidence:minimum_boundary_tasks`
- `shape:partial_required_evidence:minimum_effective_task_count`
- `shape:partial_required_evidence:minimum_nonzero_tasks`
- `shape:partial_required_evidence:positive_bootstrap_information_lcb`
- `shape:single_dimension_conflict:minimum_boundary_tasks`
- `shape:single_dimension_conflict:minimum_effective_task_count`
- `shape:single_dimension_conflict:minimum_nonzero_tasks`
- `shape:single_dimension_conflict:positive_bootstrap_information_lcb`
