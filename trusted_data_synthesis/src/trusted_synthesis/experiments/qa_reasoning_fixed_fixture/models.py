from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE: Final = "finance_qa_vnext_reasoning_bearing_fixed_fixture_constructibility_preflight_only"
DECISION: Final = (
    "finance_qa_vnext_two_frozen_archive_grounded_branch_fixtures_produce_"
    "durably_preaction_committed_observation_responsive_qualified_reasoning_"
    "trajectories_independent_audit_required"
)
NEXT_STAGE: Final = (
    "finance_qa_vnext_reasoning_bearing_fixed_fixture_constructibility_"
    "preflight_independent_audit_only"
)

EXTERNAL_REVIEW_SHA256: Final = "5a4462286fcaa14fac1e3c27bf4993a191780655286b94da4bd1f78e25785e4b"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 14_144
OPERATOR_DIRECTIVE: Final = "参照审计继续实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 24

PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_reasoning_contract_freeze_independent_audit/"
    "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_"
    "independent_audit_v1_20260905"
)
PREDECESSOR_SOURCE_COMMIT: Final = "5786b393597e3ea6955fcbb214310ab2606675d2"
PREDECESSOR_SOURCE_TREE: Final = "d856976de04b37c70198228dfdc4ae35388f837e"
PREDECESSOR_FILE_COUNT: Final = 21
PREDECESSOR_TOTAL_BYTES: Final = 81_938
PREDECESSOR_MEMBER_COUNT: Final = 20
PREDECESSOR_MEMBER_BYTES: Final = 78_675
PREDECESSOR_MANIFEST_BYTES: Final = 3_263
PREDECESSOR_MANIFEST_SHA256: Final = (
    "3d9e277f7c012d71b409d574f62d0a89378bc737d3534de68707d75698ab0ec5"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "finance_qa_reasoning_contract_independent_artifact_manifest:"
    "2af7cf54ddb7b5bee945cc72f59100cdb7073c3ba1c2304c36fced594dbc280a"
)
PREDECESSOR_ROOT_ID: Final = (
    "finance_qa_reasoning_contract_independent_artifact_root:"
    "661ac910a80064ff7c435cdc37a75204a39ba9bf10180865ce538f03cfb765f0"
)
PREDECESSOR_REPORT_ID: Final = (
    "finance_qa_reasoning_contract_independent_report:"
    "8274080a39c428ac978a3c6349b108743837e6bb01d8a04d4cf3b6265bbfe027"
)
PREDECESSOR_GATE_ID: Final = (
    "finance_qa_reasoning_contract_independent_gate:"
    "dcbc907b90c6b249eeb00cc83c786e06044bedd9c37a04d9c19d2ead4478fadd"
)
PREDECESSOR_DECISION_ID: Final = (
    "finance_qa_reasoning_contract_independent_decision:"
    "1b914ec0196ffb01f28026b75a48aaa0f247d80e6ee14ff677fc3ab5cb08e917"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "finance_qa_reasoning_contract_independent_transition:"
    "197e73b3fda8c2e32999be2cf0b56806e48bd4c1a774e7bb9384a55c74282fee"
)

ARCHIVE_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_archive_grounding/"
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_v1_20260904"
)
ARCHIVE_FILE_COUNT: Final = 24
ARCHIVE_TOTAL_BYTES: Final = 784_989
ARCHIVE_MEMBER_COUNT: Final = 23
ARCHIVE_MEMBER_BYTES: Final = 781_444
ARCHIVE_MANIFEST_BYTES: Final = 3_545
ARCHIVE_MANIFEST_SHA256: Final = "8a86354d574311631e0b38faa6acb79d13602291d4bcac350af0edfdb92b83c2"
ARCHIVE_MANIFEST_ID: Final = (
    "qa_archive_parameter_space_artifact_manifest:"
    "29dbf80f462d7dbf079df99e77d44dc5739b2a9ece8525356b43dc9ddc0f63b7"
)
ARCHIVE_ROOT_ID: Final = (
    "qa_archive_parameter_space_artifact_root:"
    "b24d054bbf6cd5275675636f7a3f69fac127b2ab1a42483911c384c1cae60f98"
)
ARCHIVE_REPORT_ID: Final = (
    "qa_archive_parameter_space_report:"
    "7669d8ba86b6bd13aabc2eed3eb332cf31b562fdc5ad30a84cbbc823bfe448d9"
)

MIXED_SIGN_ROW_ID: Final = (
    "qa_archive_parameter_case_row:4fba9ca1c78dad48c2967342be05775c8da6ae4ed1544aba5d8c4e8fbedd1e62"
)
NEAR_EQUAL_ROW_ID: Final = (
    "qa_archive_parameter_case_row:08615e003521da447a78d55af5ac14f1b0cfc69e72eb650cfcb5c87deddcf39e"
)
SELECTED_ROW_IDS: Final = (MIXED_SIGN_ROW_ID, NEAR_EQUAL_ROW_ID)

SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_fixed_fixture/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_fixed_fixture/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_fixed_fixture/runtime.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_fixed_fixture/preflight.py",
)

OBLIGATION_KINDS: Final = (
    "comparability",
    "revenue_branch",
    "operating_income_branch",
    "branch_merge",
    "final_grounding",
)

ATTACK_NAMES: Final = (
    "dispatch_without_durable_commit",
    "post_action_reasoning_backfill",
    "no_replace_envelope_overwrite",
    "fully_rehashed_envelope_receipt_substitution",
    "cross_fixture_envelope",
    "selected_executed_action_mismatch",
    "future_invisible_evidence_reference",
    "observation_claim_next_state_mismatch",
    "valid_trajectory_invalid_final_or_citation",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DurablePreactionCommitReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    envelope_id: str = Field(min_length=1)
    envelope_relative_path: str = Field(min_length=1)
    envelope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    envelope_byte_count: int = Field(gt=0)
    preaction_commit_sequence: int = Field(ge=0)
    execution_sequence: int = Field(ge=1)
    envelope_file_fsync_event: int = Field(ge=1)
    envelope_directory_fsync_event: int = Field(ge=1)
    receipt_file_fsync_event: int = Field(ge=1)
    receipt_directory_fsync_event: int = Field(ge=1)
    dispatch_event: int = Field(ge=1)
    no_replace: Literal[True] = True
    envelope_file_fsync_complete: Literal[True] = True
    envelope_directory_fsync_complete: Literal[True] = True
    schema_version: str = "durable_preaction_commit_receipt.v1"

    @model_validator(mode="after")
    def validate_receipt(self) -> DurablePreactionCommitReceipt:
        events = (
            self.envelope_file_fsync_event,
            self.envelope_directory_fsync_event,
            self.receipt_file_fsync_event,
            self.receipt_directory_fsync_event,
            self.dispatch_event,
        )
        if (
            tuple(sorted(events)) != events
            or len(set(events)) != len(events)
            or self.preaction_commit_sequence >= self.execution_sequence
            or self.receipt_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"receipt_id"}),
                prefix="durable_preaction_commit_receipt:",
            )
        ):
            raise ValueError("durable preaction receipt relation differs")
        return self
