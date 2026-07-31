from __future__ import annotations

from trusted_synthesis.core.vtdo.schema import (
    VTDORoleContract,
    vtdo_role_contract_id,
)


def make_vtdo_role_contract(
    *,
    explorer_provider_id: str,
    beneficiary_model_state_id: str,
    final_student_model_id: str,
    separation_mode: str = "strict_distinct",
    shared_role_justification_hash: str | None = None,
) -> VTDORoleContract:
    values = {
        "explorer_provider_id": explorer_provider_id,
        "beneficiary_model_state_id": beneficiary_model_state_id,
        "final_student_model_id": final_student_model_id,
        "separation_mode": separation_mode,
        "shared_role_justification_hash": shared_role_justification_hash,
    }
    provisional = VTDORoleContract.model_construct(contract_id="pending", **values)
    return VTDORoleContract(
        contract_id=vtdo_role_contract_id(provisional),
        **values,
    )
