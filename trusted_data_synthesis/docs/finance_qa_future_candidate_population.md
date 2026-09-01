# Offline Future QA Candidate Population

Date: 2026-09-01

## Decision

This stage runs a new QA synthesis path in parallel with the frozen v26.194 VTDO measurement
path. It materializes only an offline `future_QA_candidate_population` candidate Manifest. It
does not replace, extend, or become a parent of the current 32-Package, 192-Job, 792-coordinate
v26.194 condition.

The two paths remain causally separated:

```text
Frozen VTDO path
  v26.194 Package Catalog / Manifest / Runner / Execution Contract
  -> fresh artifact-backed Outcome authority
  -> later online execution under a separate authorization

Offline QA path in this stage
  SemanticTaskProposal
  -> CanonicalSemanticPlan
  -> BindingSnapshot / EvidenceCorpus / ProofGraph
  -> SemanticInstance
  -> SurfaceRealization / RealizedTaskPackage
  -> pre-outcome Candidate Manifest
  -> separate local QualityAssessment Catalog
  -> separate diversity-aware qualified projection
```

No `QAReleasePopulationManifest`, VTDO Development Population, online Job Manifest, Raw/Result
namespace, empirical Outcome row, or production Release object is created.

## Authority and Operation closure

The stage independently reruns the existing Raw Proposal compatibility audit. Its exact partition
is retained:

| Proposal | Status | Materialized packages | Candidate rows |
|---|---:|---:|---:|
| `registered_cross_metric_comparison` | authorized | 16 | 16 |
| `temporal_peak_secondary_lookup` | blocked (`argmax`, `select_by_period` absent) | 0 | 0 |
| `growth_filter_margin_rank` | blocked (five entity-table Operations absent) | 0 | 0 |

Admission does not trust the compatibility audit's `policy_contract_available` boolean alone.
Every concrete binding is compiled through `FinanceTaskPlugin`, executes the registered
`registered_compare` Operation, and passes an actual
`FinanceSemanticPolicy.validate_registered_comparison_pair()` decision. The deterministic local
candidate generator receives a narrow additive branch for the already-authorized
`registered_cross_metric_comparison` task; the old `comparison` behavior is unchanged.

The four exact registered pairs are:

```text
revenue / gross_profit
revenue / operating_income
revenue / net_income
operating_cash_flow / net_income
```

The evidence is a deterministic local engineering fixture derived from the existing Finance
counterfactual fixture builder. It is not an archive-grounded production QA sample and does not
establish realistic task-distribution quality.

## Pre-outcome identity separation

The authoritative candidate identity is
`FutureQAPreOutcomeCandidateRow`. Its identity includes:

- `semantic_task_id`, `semantic_instance_id`, `binding_snapshot_id`, and `canonical_plan_id`;
- exact Evidence Bundle and Corpus IDs and content hashes;
- exact ProofGraph ID and hash, source-record IDs, and Evidence Version IDs;
- Renderer profile, Surface Realization, and RealizedTaskPackage identities;
- Finance semantic-policy identity plus Operation semantic and implementation hashes;
- task family, task type, unmeasured difficulty label, language, market, and required Tools;
- local engineering resource estimates and their explicit non-authority labels.

It deliberately contains no `quality_assessment_id`, `execution_binding_id`, or selection flag.
The exact 16-row pre-outcome Manifest is frozen before the downstream local assessment catalog
and diversity projection are constructed.

The resource fields are explicitly:

```text
resource_estimate_status = engineering_estimate_only
runner_projection_status = not_yet_runner_projected
online_resource_authority = not_online_resource_authority
```

The local rule uses canonical public-task UTF-8 bytes as a conservative one-byte-per-token
engineering estimate and adds a 4,096-token completion reserve. These are not exact Runner Prompt
bounds and cannot authorize online execution.

## Local assessment and diversity projection

All 16 candidates execute through the deterministic local finance generator, the Finance-aware
workflow verifier, the independent Program verifier, the content-addressed
`RealizationExecutionBinding`, and `CandidateQualityEvaluator`. The resulting
`LocalAssessmentCatalog` is explicitly nonempirical:

```text
pre-outcome candidates          16
local accepted / rejected     16 / 0
semantic tasks / instances     4 / 4
Renderer surfaces per instance     4
qualified projection rows          16
diversity-selected rows              8
selected children per instance       2
exact child weight                   1/2
Provider / GPU / Development Jobs 0 / 0 / 0
```

Diversity selection consumes only hard-Gate-accepted records. It cannot compensate for a failed
realization or quality assessment. The selected eight rows are a qualified future-candidate
projection, not a production Release or empirical QA Population.

## VTDO isolation receipt

`QAVTDOIsolationReceipt` read-only parses five immutable v26.194 formal files and records their
content hashes. It confirms the unchanged frozen condition:

```text
Package Catalog          authoritative_kernel_package_catalog:cd7bee78c7ed7bc618d7b4d6441546264d1a6392336dceedee9abb89ea7e7211
Manifest                 authoritative_kernel_manifest:15da508affe0a4727f85fbc727ac1a4b6772b014fdb6a40d4e5c93ae374cd803
Runner                   authoritative_execution_kernel_runner:7a3b8ae6bfb178c351f10a00c08c18373ee61f0bf64b500f245644cc99e1e034
Execution Contract       authoritative_execution_kernel_contract:53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d
Packages / Jobs / coordinates                         32 / 192 / 792
unique Raw / Result namespaces                           192 / 192
```

The receipt is not a semantic parent of any candidate row. Candidate bytes contain none of the
v26.194 Manifest, Runner, Job, Package Catalog, Raw namespace, or Result namespace prefixes. The
QA implementation imports zero VTDO Python modules and writes zero files below the VTDO artifact
root. Only `qa_vtdo_isolation_receipt.json` is allowed to name the frozen identities; every other
formal QA file is checked against the forbidden-prefix set.

## Hard Gates

All pre-outcome hard Gates pass:

- exact one-authorized/two-blocked Proposal partition;
- actual registered-pair semantic-policy execution;
- blocked Proposal IDs absent from RealizedTaskPackages and candidate rows;
- exactly four bindings and four Renderer candidates per binding;
- pre-outcome row schema excludes assessment and selection fields;
- Evidence, Corpus, ProofGraph, source, Operation, and policy lineage is complete;
- every resource value is labeled engineering-only and non-authoritative;
- candidate bytes contain zero frozen VTDO identity/namespace token;
- the read-only isolation receipt matches 32/192/792 and 192/192 namespaces;
- Provider, GPU, Development Job, and QA Release Population Manifest counts are zero.

All downstream qualification Gates also pass: 16/16 realization validation, 16/16 hard quality
acceptance, complete execution-binding coverage, diversity-selector hard Gates, exactly two
selected children per instance, and selected-set containment within the qualified set.

Core fail-closed tests reject a resource-authority relabel and any attempt to materialize a
blocked Proposal. Tests also require byte-identical independent builds and revalidate every
formal artifact hash and size.

## Formal artifacts and identities

The deterministic formal directory is:

```text
trusted_data_synthesis/artifacts/qa_realization_vnext/
  future_qa_candidate_population_v2_20260901
```

A preliminary v1 directory remains immutable. Package-wide Mypy then exposed one local type
diagnostic where the fixture payload union was passed to a Decimal-only helper. The authoritative
v2 source explicitly normalizes that value through Decimal; candidate semantics, candidate IDs,
all local assessment outcomes, diversity selection, blocked-Proposal partition, and the v26.194
isolation receipt are unchanged. Only source-bound Manifest, Assessment, Qualification, source
Root, and artifact Root identities are refreshed.

The authoritative v2 directory contains 18 files and 1,233,274 bytes. Authoritative identities are:

```text
pre-outcome Candidate Manifest
  future_qa_preoutcome_candidate_manifest:18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad

local Assessment Catalog
  future_qa_local_assessment_catalog:c6d2a45912ca92f5640102f44ee9e4088cf0686b909495ff6fcf2dfdc48c9a19

qualification report
  future_qa_qualification_report:a5cbfd27e5b9b0bfe8c511de7131a5b8de28a1a5844b8512d0944be3dd48955b

diversity selection
  diversity_aware_release_selection:4f1377ddc1aeff75bebd24e245c3210301f3ade1dd58caea3da2264b9deb64bf

VTDO isolation receipt
  qa_vtdo_isolation_receipt:859b307646ffc623ce272744f4f968d3dd6601dfe4b54ab688fba74361a512ce

source Root
  future_qa_source_root:dbd50d8b54a02dfcc5ffee67ef309a84fbbe3e0dba066efc98d605d3af5caa22

artifact Root
  future_qa_candidate_artifact_root:9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04
```

The focused and adjacent QA suite passes 18/18. Focused PyCompile, Ruff check/format, and Mypy
pass. Package-wide Ruff passes. Package-wide no-import-follow Mypy checks 621 source files,
retains the same 70 historical or environment-dependent diagnostics in 30 predecessor files, and
reports zero diagnostics in the QA future-candidate module. No credential lookup, Provider client,
network generation, or GPU job occurs.

## Claim boundary and next use

This result shows that one authorized Operation closure can produce a parent-complete,
quality-assessed, diversity-filtered offline candidate pool without contaminating the frozen VTDO
measurement condition. It does not show model readability, online Agent success, empirical task
difficulty, archive grounding, unrestricted QA diversity, training utility, or production
readiness.

The selected eight rows may only be inputs to a later, fresh QA experiment design. Connecting
them to VTDO requires a new exact QA Population, Package Catalog, Job Manifest, Prompt evidence
set, Execution Contract, Outcome authority, credential-free preflight, and explicit online
authorization after the current frozen measurement path is resolved. They must not be inserted
into or substituted for the current v26.194 192-Job condition.
