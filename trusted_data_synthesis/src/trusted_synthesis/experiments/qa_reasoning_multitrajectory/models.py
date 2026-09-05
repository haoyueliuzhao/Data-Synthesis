"""Pre-registered scope for the two-Task, two-schedule quotient experiment."""

from __future__ import annotations

STAGE = (
    "finance_qa_vnext_reasoning_bearing_same_task_multitrajectory_"
    "quotient_constructibility_preflight_only"
)
NEXT_STAGE = (
    "finance_qa_vnext_reasoning_bearing_same_task_multitrajectory_"
    "quotient_constructibility_preflight_independent_audit_only"
)
REVIEW_BYTES = 17_346
REVIEW_SHA256 = "5e3b3bd2a79bafb0ac4088379b581d210410a6d18cfe6becd6c2858e100cc380"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
PREDECESSOR_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_reasoning_fixed_fixture_independent_audit/"
    "finance_qa_vnext_reasoning_bearing_fixed_fixture_constructibility_"
    "preflight_independent_audit_v1_20260905"
)
PREDECESSOR_MANIFEST = (
    "qa_reasoning_fixed_fixture_independent_artifact_manifest:"
    "b80cea9944bd4cad41550612f808cc0002ffd27fd98ec7957478b8459e7a6a48"
)
PREDECESSOR_ROOT = (
    "qa_reasoning_fixed_fixture_independent_artifact_root:"
    "73d0e72d13a3421a04511b78df029c64d00d15c58b41e1c963f66ed77ec2e415"
)
PREDECESSOR_SOURCE_COMMIT = "a3c430a79a5b43597d93e26aab6df40436de8b2b"
PREDECESSOR_SOURCE_TREE = "68715d5076008e74c45e2af901cf6ca2fec378ed"
PREDECESSOR_DECISION = (
    "qa_reasoning_fixed_fixture_independent_decision:"
    "96474af1423ca9377f32dc031ea581935647197f0018b352590b856503228499"
)
PREDECESSOR_TRANSITION = (
    "qa_reasoning_fixed_fixture_independent_transition:"
    "8a2641f5e6faa589d742a2c9a2928882e9177a16a58e2c4cd2603265ec59f91b"
)
SCHEDULES = (
    (
        "comparability",
        "revenue_branch",
        "operating_income_branch",
        "branch_merge",
        "final_grounding",
    ),
    (
        "comparability",
        "operating_income_branch",
        "revenue_branch",
        "branch_merge",
        "final_grounding",
    ),
)
SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_multitrajectory/" + name
    for name in (
        "__init__.py",
        "models.py",
        "runtime.py",
        "validation.py",
        "quotient.py",
        "preflight.py",
    )
)
REUSED_SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/" + name
    for name in (
        "qa_reasoning_fixed_fixture/preflight.py",
        "qa_reasoning_fixed_fixture/runtime.py",
        "qa_reasoning_fixed_fixture/models.py",
        "qa_reasoning_fixed_fixture_independent_audit/models.py",
        "qa_reasoning_fixed_fixture_independent_audit/reconstruction.py",
        "qa_reasoning_contract_freeze/models.py",
        "qa_reasoning_contract_freeze/contracts.py",
    )
)
GATE_NAMES = (
    "G0_new_external_authorization_and_exact_predecessor_freeze",
    "G1_exact_F1_F2_same_task_parent_domains",
    "G2_source_and_preregistered_schedule_quotient_contract",
    "G3_fresh_own_preaction_commitments_and_actual_actions",
    "G4_independent_own_trajectory_source_and_validity_replay",
    "G5_separate_five_depth_metrics",
    "G6_per_task_qualified_quotient_partition_computed",
    "G7_meaningful_quotient_and_runtime_controls",
    "G8_zero_Provider_expansion_mainline_and_Release_boundary",
)
