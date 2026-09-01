# Finance v26.202 Exact Empirical Evaluation And First-Response Interface Localization

Audit date: 2026-09-02

## Scope And Decision

Finance v26.202 consumes only:

```text
v26_200_exact_empirical_evidence_set_evaluation_and_first_response_
interface_localization_only
```

The exact 10,706-byte external review is bound at SHA-256
`b534d14cf53d5ed6fbb65f59647f8e244e220f3ea160f85b74ac47da2724034e`. It accepts
the v26.200 one-shot online execution and the v26.201 evidence audit, while correcting the
interpretation of the frozen end-to-end estimands. This stage makes zero Provider calls, reads no
credential, changes no historical response, and creates no replacement, rerun, recovery, Mapper,
State, frequency, Contribution, or VTDO row.

The formal decision is:

```text
end_to_end_zero_capability_rates_materialized_and_first_response_
interface_structurally_localized
```

This is an exact empirical evaluation of the already frozen 192-Job execution and a read-only
first-Prompt localization. It is not a Prompt repair, model rerun, or post-hoc parser adaptation.

## v26.201 Interpretation Correction

The v26.201 evidence conclusion remains accepted: all 192 Jobs have unique and independently
reconstructed Raw, Result, Trace, Outcome, terminal, and FailureLocus evidence. Its statement that
no estimate was materialized in v26.201 is also correct as a stage-permission fact.

The causal claim that zero Action-ABI crossings made the end-to-end estimands unavailable is
superseded. The frozen denominators are all exact Manifest Jobs, not only Jobs that crossed the
Action ABI. The exact 188 `first_response_abi_invalid` and four `thinking_integrity_failure` rows
therefore remain in both denominators:

```text
q_first numerator / denominator                0 / 192
q_bounded_correction numerator / denominator   0 / 192
post-Action-ABI semantic denominator            0
post-Action-ABI conditional semantic rate       null
post-Action-ABI trajectory-depth capability     null
```

Intermediate Action acceptance and Verifier factors remain unevaluable on pre-ABI terminals,
while the compound event “complete Qualified Job” is false. Those statements are compatible.

## Exact-Set Evaluator Binding

v26.202 revalidates the exact v26.195 Catalog, Manifest, Runner, Execution, Terminal Registry,
Raw, Result, Trace, Outcome, and evaluator Contract parents through the frozen v26.195 parent
validator. It binds evaluator Contract
`fresh_exact_evidence_set_evaluator_contract:af7f9630a81ea9227570996e8e3a60ddebd1cef2a82d3257c0d90f1fd247f62b`.

One implementation fact is recorded explicitly rather than hidden: the frozen v26.195 public
entry point is preflight-only. Its source rejects every evidence kind other than
`scripted_preflight_control`, its Contract says empirical evaluation and estimate materialization
are false, and its scripted reconstruction assumes `completed_qualified`. The v26.200 empirical
Trace also intentionally extends the preflight Trace with integration and Provider parents.
Therefore v26.202 does not pretend that the old public function directly accepted the empirical
rows. The new external audit supplies a content-addressed empirical-authorization overlay; the
overlay preserves v26.195 exact-set and parent-validation semantics, validates the v26.200
empirical Bundle types and actual artifact bytes, and materializes only the already frozen
end-to-end fractions. No v26.195 or v26.200 byte is changed.

The exact Evaluation identity is
`finance_v26_202_exact_empirical_evidence_set_evaluation:0c055496991bb3e37dba0f18bada7b87a3a60d857ce9652d677b785002864e23`.

## Exact First-Prompt Reconstruction

For each exact Job, the audit reconstructs the first Runtime State and Prompt by the same frozen
chain used online:

```text
v26.194 Job
  -> v26.192 JsonExplicit Job
  -> frozen Runtime Job
  -> prepare_job / initialize / render_next_prompt
  -> v26.192 action_core / JSON-explicit renderer
  -> exact Stage 1 request body and certificates
```

All 192 reconstructed Prompt SHA-256 values match the `request_hash` persisted in the actual
Provider telemetry. The 188 ordinary response rows also have persisted privacy envelopes; every
reconstructed PreparedRequest and DynamicRequestCertificate identity matches those envelopes.
The four `ReasoningBudgetExhaustedError` rows have no Kernel envelope because the client raised
after collecting telemetry and before Kernel journaling. Their Prompt hashes remain independently
matched from Raw telemetry; missing envelope identities are recorded as unavailable rather than
fabricated.

All requests contain exactly one `user` message and zero `system` messages. The public task,
Candidate table, response ABI object, and generic JSON-output instruction therefore share one
message role; no stronger role priority separates them.

## Schema-Source Matrix

The exact Action parser requires:

```text
action_id
decision_kind
protocol
state_id
```

In all 192 rendered Prompts, the object named `response_abi` directly contains `state_id`,
`decision_kind`, and `protocol`, plus `grammar_id`, but does not contain an explicit `action_id`
field. `action_id` appears separately inside every Candidate row. Thus the four parser-required
fields are model-visible but are not presented as one contiguous four-field response object.

The public semantic Task also exposes `answer_fields`, and exposes per-operator output field lists
under `operator_output_fields`. Under canonical JSON ordering, both declarations precede the
`response_abi` object in all 192 Prompts; the generic instruction “Return exactly one valid JSON
object matching the response ABI” appears after it. This is a structural ordering fact, not an
instruction-following causal estimate.

The response/source matrix closes as follows:

```text
public JSON responses                                      188
exact Action-ABI responses                                   0
exact Answer-Schema matches                                167
exact Operation-output-Schema matches                      167
exact Answer-or-Operation matches                          167
  difference | higher_ref                                 128
  value                                                     39
other partial Action/Candidate/result shapes                21
```

Field-level results are:

```text
difference  actual responses 128; Answer prompts 144; Operation-output prompts 192
higher_ref  actual responses 128; Answer prompts 144; Operation-output prompts 192
value       actual responses  39; Answer prompts  48; Operation-output prompts 192
action_id   actual responses  16; direct response_abi prompts 0; Candidate prompts 192
```

The remaining 21 responses span nine shapes. Twenty use partial Action/Candidate fields, including
combinations of `action_id`, `state_id`, `decision_kind`, `choice_handle`, `command`,
`presentation_index`, and `schema_version`; one uses `choice_handle` only, while three shapes also
contain a `result` field. None crosses the exact four-field parser.

This proves that a competing task Answer/Operation output Schema is visibly present and exactly
matches the two dominant response shapes. It strongly supports a Prompt-interface ambiguity
hypothesis. It does not prove that this structural overlap caused the model responses; private
reasoning content is absent, and no counterfactual Prompt was executed in this stage.

## Destructive Controls

Eight actual controls reject:

1. one Manifest Job removed;
2. one Job duplicated while replacing the last row;
3. all four Thinking terminals excluded;
4. one terminal reclassified as `completed_qualified`;
5. one Prompt byte changed;
6. one Prompt crossed with another Job's envelope;
7. historical public payload adapted into an Action;
8. one external-audit byte added.

All eight reject at exact-set, empirical Bundle, Prompt request-hash, historical-adaptation, or
authorization boundaries. Accepted attacks and Provider calls are zero. Destructive Audit
identity is
`finance_v26_202_destructive_audit:da90a57eb4be4c5d312f02bafd536123d51d741edb73015d46709a0e82086970`.

## Authoritative Identities And Validation

- external authorization:
  `finance_v26_202_external_audit_authorization:2e4154ff64423d630ff3ebd7225bd0d97a95aa7f515d6ca7c5611d0258708735`;
- v26.201 Freeze:
  `finance_v26_202_v201_audit_freeze:571208ecdf1aa3df5df966fb7420bff602b07da04c87cd765db3fb2c91b4a39a`;
- exact empirical Evaluation:
  `finance_v26_202_exact_empirical_evidence_set_evaluation:0c055496991bb3e37dba0f18bada7b87a3a60d857ce9652d677b785002864e23`;
- first-response localization:
  `finance_v26_202_first_response_interface_localization:45956f898d66005e6d8b49177b7bbf4b9ece7b9682c16d9e782d6c9cbce783ea`;
- Decision:
  `finance_v26_202_decision:79d4dc83e6aea9fce43ae2c5016a1f7ad5c5a66bb888281696b68ebc70d1a3aa`;
- Transition:
  `finance_v26_202_transition:e2eb5e4004d4bd744800e9c54222fd877aefe42b3fed85ececec38aa35595163`;
- Artifact Manifest:
  `finance_v26_202_artifact_manifest:6e80c2f33a92705d82e1dd6c4f9097db5103658dae487f26255af1a847fe3022`;
- Artifact Root:
  `finance_v26_202_artifact_root:1c41c278c4c879586160715822a48ed9e8a39deb4fe9ca8b950e871424245b87`.

The exact source commit/tree are:

```text
a4508dc1c896cb13533f2838d3d74d08d75a40ef
6fb1bf2ee025ed4db1a6910b5500626e1ac3d09f
```

The formal directory contains eleven files and 674,872 bytes. Two independent pre-freeze builds
were byte-identical. The authoritative-source build is separately rebuilt from an empty directory
and compared byte for byte. Focused Pytest, PyCompile, Ruff check/format, no-import-follow Mypy,
the adjacent v26.200-v26.202 regression, and package-wide Ruff are recorded in the final project
status.

## Current Boundary

The current decision returns to:

```text
no_further_experiment_authorized_without_new_audit_decision
```

No Prompt/interface repair, parser relaxation, old-response adaptation, Provider call, recovery,
or full 192-Job rerun is authorized. If a later audit authorizes a repair, the repair must receive
a fresh identity and should first pass a fresh, stratified, small-scale Action-interface online
calibration before any new full experiment condition is considered.
