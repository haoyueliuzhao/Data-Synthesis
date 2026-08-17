# Finance v26.55 Executable-Support Contract Hardening

Audit date: 2026-08-18

## Summary

Finance v26.55 is a credential-free hardening replication of v26.54. It was triggered by a
prospective contract audit after the v26.54 implementation and immutable result had been committed
at `c67671c`.

The audit found two contract issues that did not alter the current 24-task negative result but
would have made a future positive result unsound:

1. Public Witness validity did not record Citation completeness as an explicit component of
   `V=1`;
2. a task that passed capability-measurement requirements but lacked three VTDO paths would be
   rejected by the shared blocker validator instead of being admitted only to the capability role.

The v2 contract repairs both issues, adds a target-mechanism identity check to every necessity
counterfactual, and preserves content-hash replay for historical v1 Witness artifacts. It then
rebuilds all 24 tasks from the same immutable v26.42/v26.53 inputs.

The scientific result is unchanged:

```text
Public executable witness                 18 / 24
Typed answer projection bound              0 / 24
Evidence support lattice bound              0 / 24
Mechanism necessity proved                  0 / 24
Three model-owned valid paths proved        0 / 24
Capability-measurement eligible             0 / 24
VTDO-multistate eligible                     0 / 24
```

The authoritative v2 result remains blocked at:

```text
capability_task_or_scaffold_redesign_only
```

## Versioned Changes

### Citation-complete Public Witness

`PublicExecutableWitnessArtifact` v2 adds:

```text
cited_evidence_ids
citation_complete
```

Citation IDs must be sorted, unique, selected by the public execution, and nonempty when the
attestation is complete. The Witness validity conjunction is now:

```text
only_public_inputs
and only_allowed_tools
and operation_lineage_complete
and evidence_support_complete
and verification_complete
and answer_projection_complete
and citation_complete
```

All 24 current tasks selected and cited the complete Gold support before any later failure. Thus
Citation completeness is `24/24`; it does not rescue the six tasks whose required normalization
tool is absent. Complete Witness validity remains `18/24`.

Historical v1 Witness IDs exclude the two new v2 fields during identity replay. A dedicated test
reconstructs a v1 identity under the old hash semantics; v2 artifacts require a non-null Citation
attestation and use the new schema identity.

### Role-specific Admission

The corrected role logic is:

```text
blocked:
  capability prerequisites fail

capability_measurement:
  capability prerequisites pass
  but three VTDO paths do not pass

vtdo_multistate:
  capability prerequisites pass
  and three VTDO paths pass
```

A new positive contract test materializes the middle case and verifies that it is admitted as
`capability_measurement`, while retaining the three-path blocker for VTDO. This prevents task-role
conflation without lowering either role's requirements.

### Counterfactual Target Identity

Every `MechanismCounterfactualResult.mutation_target` must now equal its enclosing
`MechanismNecessityArtifact.target_mechanism_id`. A deletion or bypass result for another
mechanism cannot satisfy the required mutation-family denominator.

## Frozen Inputs

v26.55 uses the same source bytes as v26.54:

| Input | Identity |
| --- | --- |
| v26.42 compiled proof artifacts | `43f634ec9c01a620277162e5cf41bc7060ca51240fa10eba5c0317c6eabd1959` |
| v26.42 Development Population | `effac9dd84012ed15dfa734b62a04dc1861c49d95938d442054cf1de0e3164fd` |
| v26.53 statistical audit | `finance_v26_bridge_statistical_audit:c7851d1487fbab1c5d4814451ea3f46aa52f54e68f01bc841cd66acfcd43c64b` |
| v26.53 report bytes | `feb52d559b9e0493456cac7d89edf70fff1eb3a3771b59ae667ed6b482359d95` |

No task, Evidence, threshold, mechanism assignment, or prior outcome was changed.

## Immutable Outputs

The v2 report identity is:

```text
finance_v26_executable_support_audit:9f3b34ae4fcb75fb7226ba9d5e67a20fe5e596d8fb45bdf689208d5323c9bbae
```

Artifact root:

```text
artifacts/vtdo_experiment/finance_v26_55_executable_support_contract_v2_20260818/
```

| Artifact | Records | SHA-256 |
| --- | ---: | --- |
| Typed Answer Projection contracts | 24 | `8d6233448947ab7bd2ba5c7e242da9fa22a1365fac7a3a061211d4ff970e980d` |
| Public Executable Witnesses | 24 | `c723eed5c26ce9a3e0c4a3c6ca04171da4c2e5a1a938ca142b16cf42499d8073` |
| Public Witness Observations | 226 | `f66ed3b1e773d4d2fcaed432463dbb824ad50c036472d424ea9d67a505a9c84f` |
| Evidence Support Lattices | 24 | `376d12738d9b705bfca2ed09ea6aea735c39448efb3f8b69b7a66213f7911ed1` |
| Mechanism Necessity artifacts | 24 | `b350b89266bffcc967171410ab0633d63199ff7131d78d93d6c9bdb31a1b0fd1` |
| Alternative Valid Path catalogs | 24 | `ccbad4aee2d7ea6642c63460f9ae3b8e843a07ac0408235a841c675649b8aa6b` |
| Task support compilations | 24 | `69602b4577c36fff2de72bf78f5f1043bfb081a6f7d38a543f702c0cb6dd05cf` |

The compiler version is `1.1.0`; the experiment schema is
`finance_v26_executable_support_audit.v2`; all newly emitted support artifacts use
`executable_support_contract.v2`.

## Interpretation

v26.55 supersedes v26.54 only as the contract for future task construction. It does not mutate or
invalidate the v26.54 historical run. The unchanged counts show that the v26.54 blocker was not an
artifact of omitted Citation accounting or task-role conflation.

Supported conclusions remain:

- 18 current tasks have a complete public executable solution under the strict v2 contract;
- six tasks fail before normalization because Allowed Tools are incomplete;
- all current tasks lack bound Projection/Lattice contracts and mechanism-necessity proofs;
- no current task has three model-owned, state-distinct valid paths;
- no online stage is authorized.

The run used zero model API calls and zero GPU jobs. Fresh Confirmation, State-support Discovery,
No-C VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution is zero.

## Next Step

All newly rematerialized tasks must use the v2 contract. The next no-API Population builder must:

1. close Allowed Tools against required operations before task identity freeze;
2. bind Typed Answer Projection and Evidence Support Lattice to the Verifier;
3. prove mechanism necessity with target-matched counterfactuals;
4. classify capability-only and VTDO-multistate tasks separately;
5. require Citation-complete Public Witnesses for both roles;
6. require three model-owned, Scaffold-invariant states only for the VTDO role.

No API Development may start until those static requirements pass on the fresh selected
Population.
